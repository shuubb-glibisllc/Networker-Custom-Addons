# Odoo RAG Integration

This project is configured to use the central Odoo RAG system.

## For Claude Code Sessions

Claude Code can directly import and use the Odoo documentation search:

```python
# In Claude Code, use this to get Odoo documentation context:
from odoo_helper import quick_search

context = quick_search("How to create custom models?")
# This will return formatted Odoo documentation context
```

## Claude Code Tool Configuration

The project includes:
- `settings.local.json` - Configures the `odoo_docs` custom tool
- `odoo_helper.py` - Provides the quick_search function

Claude Code will automatically have access to the `odoo_docs` tool.

## Manual Usage

```python
from odoo_helper import quick_search
result = quick_search("security groups access rules")
print(result)
```

## Central RAG Location
/home/shuubb/Desktop/Odoo AI

This setup avoids duplicating the 438MB documentation across projects.
