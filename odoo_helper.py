#!/usr/bin/env python3
"""
Odoo RAG Helper - Links to central installation
Central RAG location: /home/shuubb/Desktop/Odoo AI
"""

import sys
from pathlib import Path

# Point to central RAG installation
CENTRAL_RAG_PATH = Path("/home/shuubb/Desktop/Odoo AI")

# Add central RAG to Python path
if str(CENTRAL_RAG_PATH) not in sys.path:
    sys.path.insert(0, str(CENTRAL_RAG_PATH))

try:
    from claude_code_rag_tool import (
        odoo_help, 
        odoo_docs_tool,
        odoo_models_help, 
        odoo_views_help, 
        odoo_security_help, 
        odoo_api_help
    )
    
    def quick_search(query: str) -> str:
        """Quick Odoo documentation search"""
        return odoo_help(query)
    
    def search_models(query: str = "create custom models") -> str:
        """Search for model-related documentation"""
        return odoo_models_help(query)
    
    def search_views(query: str = "create views") -> str:
        """Search for view-related documentation"""  
        return odoo_views_help(query)
    
    def search_security(query: str = "security access rules") -> str:
        """Search for security-related documentation"""
        return odoo_security_help(query)
    
    def search_api(query: str = "API web services") -> str:
        """Search for API-related documentation"""
        return odoo_api_help(query)
    
    # Success message
    print("✅ Odoo RAG linked successfully!")
    print(f"🔗 Using central installation: {CENTRAL_RAG_PATH}")
    print("📖 Available functions:")
    print("   - quick_search(query)")
    print("   - search_models(query)")
    print("   - search_views(query)")
    print("   - search_security(query)")
    print("   - search_api(query)")
    
except ImportError as e:
    print(f"❌ Cannot link to central RAG installation: {e}")
    print(f"📍 Expected location: {CENTRAL_RAG_PATH}")
    print("💡 Make sure central RAG is properly installed")
    print("💡 Run setup in central location first")

# For direct script usage
if __name__ == "__main__":
    try:
        result = quick_search("How to create custom models?")
        print("\n" + "="*50)
        print("SAMPLE SEARCH RESULT:")
        print("="*50) 
        print(result[:500] + "..." if len(result) > 500 else result)
    except Exception as e:
        print(f"Test search failed: {e}")
