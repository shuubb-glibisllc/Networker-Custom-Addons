# -*- coding: utf-8 -*-
import base64
import json
import random
import re
import time
import logging
import requests
import html as _html
import subprocess
import tempfile
from urllib.parse import urljoin

from odoo import fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

# ---- Endpoints
CAPTCHA_ENTRY_URL = "https://enreg.reestri.gov.ge/main.php?m=new_index"
CAPTCHA_SEED_URL  = "https://enreg.reestri.gov.ge/simple-php-captcha-master/icaptcha.php"
CAPTCHA_IMG_URL   = "https://enreg.reestri.gov.ge/simple-php-captcha-master/simple-php-captcha.php"
RESULT_URL        = "https://enreg.reestri.gov.ge/main.php"        # show_legal_person / show_app
SEARCH_URL        = "https://enreg.reestri.gov.ge/main.php"        # VAT search
DEA_RESULT_URL    = "https://enreg.reestri.gov.ge/_dea/main.php"   # _dea show_app sometimes lives here
DJVU_HOST         = "https://bs.napr.gov.ge"

# ---- Patterns
DJVU_SIG = b"AT&TFORM"
ID_REGEX = re.compile(r"საიდენტიფიკაციო კოდი</td>\s*<td><strong>(\d+)</strong>")
LEGAL_REGEX = re.compile(r"show_legal_person\((\d+)\)", re.I)
PID_REGEX   = re.compile(r"show_app\((\d+)\s*,", re.I)

# greedy but safe: handles single/double quotes, relative/absolute urls, &amp; etc.
DOC_REGEX = re.compile(r"""
    href\s*=\s*
    (?P<q>["'])
    (?P<url>
        (?:https?:)?//?bs\.napr\.gov\.ge/[^"']*GetBlob\?[^"']+   # absolute (with/without scheme)
        |
        [^"']*GetBlob\?[^"']+                                     # relative
    )
    (?P=q)
    [^>]*>
    \s*(?P<name>[^<]*\.djvu)
""", re.I | re.X)

class PartnerNaprFetchWizard(models.TransientModel):
    _name = "partner.napr.fetch.wizard"
    _description = "Fetch NAPR Documents"

    partner_id    = fields.Many2one("res.partner", required=True, ondelete="cascade")
    vat           = fields.Char(readonly=True)
    captcha_image = fields.Binary(string="CAPTCHA", readonly=True)
    captcha_text  = fields.Char(string="Enter CAPTCHA")
    convert_to_pdf = fields.Boolean(string="Convert DJVU to PDF", default=True, 
                                   help="Automatically convert DJVU files to PDF format")
    _cookie_json  = fields.Text(string="Session Cookies", readonly=True)

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _new_session(self) -> requests.Session:
        s = requests.Session()
        s.headers.update({
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "Referer": CAPTCHA_ENTRY_URL,
        })
        _logger.debug("NAPR: new session UA=%s", s.headers["User-Agent"])
        return s

    def _session_from_cookies(self) -> requests.Session:
        s = self._new_session()
        if self._cookie_json:
            try:
                ck = json.loads(self._cookie_json)
                jar = requests.cookies.RequestsCookieJar()
                for k, v in ck.items():
                    jar.set(k, v, domain="enreg.reestri.gov.ge", path="/")
                s.cookies = jar
                _logger.debug("NAPR: restored cookies: %s", ck)
            except Exception as e:
                _logger.warning("NAPR: failed to restore cookies: %s", e)
        return s

    def _dump_text(self, path_base: str, data: str | bytes):
        try:
            p = f"/tmp/{path_base}.{'bin' if isinstance(data, (bytes, bytearray)) else 'html'}"
            with open(p, "wb" if isinstance(data, (bytes, bytearray)) else "w", encoding=None if isinstance(data, (bytes, bytearray)) else "utf-8", errors=None if isinstance(data, (bytes, bytearray)) else "ignore") as f:
                f.write(data)
            _logger.warning("NAPR: dumped to %s (len=%d)", p, len(data or b""))
        except Exception as e:
            _logger.warning("NAPR: failed to dump %s: %s", path_base, e)

    def _decode_html(self, r: requests.Response) -> str:
        # Let requests sniff encoding; if undecided, force utf-8 (ignore errors)
        r.encoding = r.apparent_encoding or "utf-8"
        try:
            return r.text
        except Exception:
            return r.content.decode("utf-8", "ignore")

    def _abs_getblob(self, raw: str) -> str:
        url = _html.unescape((raw or "").strip())
        if url.startswith("//"):
            url = "https:" + url
        elif url.startswith("/"):
            url = urljoin(DJVU_HOST, url)
        elif not url.lower().startswith("http"):
            url = urljoin(DJVU_HOST + "/", url)
        return url

    def _extract_company_id(self, html: str) -> str:
        m = ID_REGEX.search(html or "")
        return m.group(1) if m else ""

    def _extract_legal_name(self, html: str) -> str:
        """Extract legal name from the search results table"""
        import re
        
        # Based on your example, the name is in a td with whitespace around it
        # Look for pattern like: <td valign="top">     შპს ტრონიქს ჯორჯია  </td>
        name_pattern = r'<td valign="top">\s*([^\d<][^<]*?)\s*</td>'
        matches = re.findall(name_pattern, html or "", re.DOTALL | re.MULTILINE)
        
        for match in matches:
            cleaned = match.strip()
            # Valid company name: 
            # - Not empty, not just numbers
            # - Not status text like "აქტიური"
            # - Not legal form like "შეზღუდული პასუხისმგებლობის საზოგადოება"
            # - Contains Georgian characters or common prefixes
            if (cleaned and 
                not re.match(r'^\d+$', cleaned) and
                cleaned not in ['', '&nbsp;'] and
                'აქტიური' not in cleaned and
                'შეზღუდული პასუხისმგებლობის საზოგადოება' not in cleaned and
                ('შპს' in cleaned or 'ოოო' in cleaned or 'სს' in cleaned or
                 any('ა' <= c <= 'ჰ' for c in cleaned))):
                return cleaned
                
        return ""

    def _extract_docs(self, html: str, vat: str, company_id: str):
        docs = []
        # primary: paired link + visible .djvu name
        for m in DOC_REGEX.finditer(html or ""):
            url = self._abs_getblob(m.group("url"))
            name = (m.group("name") or "").strip() or "document.djvu"
            docs.append({"vat": vat, "company_id": company_id, "file_name": name, "bid_url": url})

        # fallback: any GetBlob?… even if no adjacent .djvu text
        if not docs:
            for raw in re.findall(r'(?:https?:)?//?bs\.napr\.gov\.ge/[^"\'<>]*GetBlob\?[^"\'<>]+', html or "", flags=re.I):
                docs.append({
                    "vat": vat, "company_id": company_id,
                    "file_name": "attachment.djvu",
                    "bid_url": self._abs_getblob(raw),
                })
        _logger.debug("NAPR: extracted %d docs (company_id=%s)", len(docs), company_id)
        return docs

    def _convert_djvu_to_pdf(self, djvu_content: bytes, filename: str) -> tuple[bytes, str]:
        """
        Convert DJVU content to PDF using ddjvu system tool
        Returns: (content_bytes, new_filename)
        """
        if not self.convert_to_pdf:
            return djvu_content, filename
            
        try:
            with tempfile.NamedTemporaryFile(suffix='.djvu', delete=False) as djvu_file, \
                 tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as pdf_file:
                
                # Write DJVU data
                djvu_file.write(djvu_content)
                djvu_file.flush()
                
                # Convert using ddjvu (requires djvulibre-bin package)
                result = subprocess.run([
                    'ddjvu', '-format=pdf', djvu_file.name, pdf_file.name
                ], capture_output=True, timeout=60, text=True)
                
                if result.returncode == 0:
                    # Read the converted PDF
                    with open(pdf_file.name, 'rb') as f:
                        pdf_content = f.read()
                    
                    if pdf_content:
                        new_filename = filename.replace('.djvu', '.pdf')
                        _logger.info("NAPR: converted %s to PDF (%d bytes)", filename, len(pdf_content))
                        return pdf_content, new_filename
                else:
                    _logger.warning("NAPR: ddjvu conversion failed for %s: %s", filename, result.stderr)
                    
        except FileNotFoundError:
            _logger.error("NAPR: ddjvu command not found. Install djvulibre-bin package.")
        except subprocess.TimeoutExpired:
            _logger.error("NAPR: ddjvu conversion timeout for %s", filename)
        except Exception as e:
            _logger.warning("NAPR: DJVU to PDF conversion failed for %s: %s", filename, e)
        finally:
            # Cleanup temp files
            try:
                import os
                if 'djvu_file' in locals():
                    os.unlink(djvu_file.name)
                if 'pdf_file' in locals():
                    os.unlink(pdf_file.name)
            except:
                pass
        
        # Return original if conversion fails
        return djvu_content, filename

    # -------------------------------------------------------------------------
    # VAT -> legal_code_id
    # -------------------------------------------------------------------------
    def _resolve_legal_code_id(self, session: requests.Session, vat: str) -> str:
        params = {"c": "search", "m": "find_legal_persons", "s_legal_person_idnumber": vat.strip()}
        r = session.get(SEARCH_URL, params=params, timeout=30)
        html = self._decode_html(r)
        _logger.debug("NAPR: search url=%s status=%s len=%d", r.url, r.status_code, len(html))
        r.raise_for_status()
        found = LEGAL_REGEX.findall(html)
        if not found:
            self._dump_text(f"napr_search_{vat}", html)
            _logger.error("NAPR: could not resolve legal_code_id for VAT=%s", vat)
            return ""
        _logger.info("NAPR: resolved legal_code_id=%s for VAT=%s", found[0], vat)
        return found[0]

    # -------------------------------------------------------------------------
    # Actions
    # -------------------------------------------------------------------------
    def action_refresh_captcha(self):
        self.ensure_one()
        if not (self.partner_id.vat or "").strip():
            raise UserError(_("Set Legal Code ID (VAT) on the contact first."))

        s = self._new_session()
        _logger.info("NAPR: refreshing CAPTCHA for VAT=%s", self.partner_id.vat)

        s.get(CAPTCHA_ENTRY_URL, timeout=20)
        s.get(CAPTCHA_SEED_URL,  timeout=20)

        t_param = f"{random.random():.8f} {int(time.time())}"
        r = s.get(CAPTCHA_IMG_URL, params={"_CAPTCHA": "", "t": t_param}, timeout=20)
        _logger.debug("NAPR: captcha url=%s status=%s bytes=%d", r.url, r.status_code, len(r.content))
        r.raise_for_status()

        self.write({
            "captcha_image": base64.b64encode(r.content),
            "_cookie_json": json.dumps(s.cookies.get_dict()),
            "vat": self.partner_id.vat,
        })
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_fetch_and_attach(self):
        self.ensure_one()
        if not (self.captcha_text or "").strip():
            raise UserError(_("Enter the CAPTCHA."))
        if not (self.partner_id.vat or "").strip():
            raise UserError(_("Set Legal Code ID (VAT) on the contact first."))

        vat = self.partner_id.vat.strip()
        cap = self.captcha_text.strip()
        _logger.info("NAPR: fetch partner=%s VAT=%s captcha='%s' convert_pdf=%s", 
                    self.partner_id.display_name, vat, cap, self.convert_to_pdf)

        s = self._session_from_cookies()

        # 1) VAT -> legal_code_id
        legal_code_id = self._resolve_legal_code_id(s, vat)
        if not legal_code_id:
            raise UserError(_("Could not resolve legal_code_id for VAT %s") % vat)

        # 2) show_legal_person
        params = {"c": "app", "m": "show_legal_person", "legal_code_id": legal_code_id, "enteredCaptcha": cap}
        r = s.get(RESULT_URL, params=params, timeout=30)
        html = self._decode_html(r)
        _logger.debug("NAPR: show_legal_person url=%s status=%s len=%d", r.url, r.status_code, len(html))
        r.raise_for_status()

        docs = []
        if "GetBlob" in html:
            company_id = self._extract_company_id(html)
            docs = self._extract_docs(html, vat, company_id)
        else:
            # 3) fallback via show_app pid(s)
            pids = PID_REGEX.findall(html)
            _logger.info("NAPR: GetBlob not on show_legal_person; show_app app_ids=%s", pids)
            if not pids:
                self._dump_text(f"napr_result_{vat}", html)
                raise UserError(_("No documents found or CAPTCHA incorrect."))

            for pid in pids:
                # try _dea first (observed by you), then normal
                tried = []
                for base_url in (DEA_RESULT_URL, RESULT_URL):
                    tried.append(base_url)
                    rp = s.get(base_url, params={"c": "app", "m": "show_app", "app_id": pid,
                                                 "parent": "personPage", "personID": ""}, timeout=30)
                    h2 = self._decode_html(rp)
                    _logger.debug("NAPR: show_app app_id=%s url=%s status=%s len=%d",
                                  pid, rp.url, rp.status_code, len(h2))
                    rp.raise_for_status()
                    if "GetBlob" in h2:
                        docs.extend(self._extract_docs(h2, vat, pid))
                        break  # stop trying base urls for this pid

        if not docs:
            # dump both the page and raw bytes for inspection
            self._dump_text(f"napr_result_{vat}", html)
            self._dump_text(f"napr_result_{vat}", r.content)
            raise UserError(_("No .djvu links found on the page."))

        # 4) Attach downloads
        Attachment = self.env["ir.attachment"]
        created = 0
        converted = 0
        
        for d in docs:
            try:
                fr = s.get(d["bid_url"], timeout=60)
                fr.raise_for_status()
                content = fr.content or b""
                ctype = (fr.headers.get("Content-Type") or "").lower()
                _logger.debug("NAPR: GET %s -> ctype=%s bytes=%d", d["bid_url"], ctype, len(content))
                
                if not (content.startswith(DJVU_SIG) or "djvu" in ctype):
                    _logger.info("NAPR: skip %s (not djvu)", d["file_name"])
                    continue

                # Convert DJVU to PDF if requested
                final_content, final_name = self._convert_djvu_to_pdf(content, d["file_name"])
                
                # Track if conversion happened
                if final_name.endswith('.pdf') and d["file_name"].endswith('.djvu'):
                    converted += 1
                    final_mimetype = "application/pdf"
                else:
                    final_mimetype = fr.headers.get("Content-Type") or "image/vnd.djvu"

                # Check for duplicates
                exists = Attachment.search([
                    ("res_model", "=", "res.partner"),
                    ("res_id", "=", self.partner_id.id),
                    ("name", "=", final_name),
                ], limit=1)
                if exists:
                    _logger.info("NAPR: duplicate %s skipped", final_name)
                    continue

                Attachment.create({
                    "name": final_name,
                    "res_model": "res.partner",
                    "res_id": self.partner_id.id,
                    "datas": base64.b64encode(final_content),
                    "mimetype": final_mimetype,
                })
                created += 1
                _logger.info("NAPR: attached %s (%d bytes)", final_name, len(final_content))
                
            except Exception as e:
                _logger.warning("NAPR: failed downloading %s: %s", d.get("file_name"), e)

        # Build result message
        if created:
            msg_parts = [f"Attached {created} file(s)"]
            if converted:
                msg_parts.append(f"({converted} converted to PDF)")
            msg = " ".join(msg_parts) + "."
        else:
            msg = "No new files attached."
            
        _logger.info("NAPR: done VAT=%s legal_code_id=%s -> %s", vat, legal_code_id, msg)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": "NAPR", "message": msg, "sticky": False},
        }

    def action_fetch_legal_name(self):
        """Fetch legal name from Georgian registry and update partner name"""
        self.ensure_one()
        if not (self.partner_id.vat or "").strip():
            raise UserError(_("Set Legal Code ID (VAT) on the contact first."))

        vat = self.partner_id.vat.strip()
        _logger.info("NAPR: fetching legal name for VAT=%s", vat)

        s = self._new_session()
        
        # Search for the company using VAT
        params = {"c": "search", "m": "find_legal_persons", "s_legal_person_idnumber": vat}
        r = s.get(SEARCH_URL, params=params, timeout=30)
        html = self._decode_html(r)
        _logger.debug("NAPR: search url=%s status=%s len=%d", r.url, r.status_code, len(html))
        r.raise_for_status()

        # Extract legal name from the response
        legal_name = self._extract_legal_name(html)
        if not legal_name:
            self._dump_text(f"napr_legal_name_search_{vat}", html)
            raise UserError(_("Could not find legal name for VAT %s") % vat)

        # Update partner name
        self.partner_id.write({"name": legal_name})
        
        _logger.info("NAPR: updated partner name to '%s' for VAT=%s", legal_name, vat)
        return {
            "type": "ir.actions.act_window",
            "res_model": "res.partner",
            "res_id": self.partner_id.id,
            "view_mode": "form",
            "target": "current",
        }