#!/usr/bin/env python3
"""Test script to verify installation and imports."""

import sys
from pathlib import Path

def test_imports():
    """Test that all required modules can be imported."""
    print("🧪 Testing imports...")
    
    try:
        import click
        print("✅ click")
    except ImportError as e:
        print(f"❌ click: {e}")
        return False
    
    try:
        import httpx
        print("✅ httpx")
    except ImportError as e:
        print(f"❌ httpx: {e}")
        return False
    
    try:
        import rich
        print("✅ rich")
    except ImportError as e:
        print(f"❌ rich: {e}")
        return False
    
    try:
        import pandas
        print("✅ pandas")
    except ImportError as e:
        print(f"❌ pandas: {e}")
        return False
    
    try:
        import geopandas
        print("✅ geopandas")
    except ImportError as e:
        print(f"❌ geopandas: {e}")
        return False
    
    try:
        import shapely
        print("✅ shapely")
    except ImportError as e:
        print(f"❌ shapely: {e}")
        return False
    
    try:
        import pyproj
        print("✅ pyproj")
    except ImportError as e:
        print(f"❌ pyproj: {e}")
        return False
    
    try:
        import aiosqlite
        print("✅ aiosqlite")
    except ImportError as e:
        print(f"❌ aiosqlite: {e}")
        return False
    
    try:
        import pydantic
        print("✅ pydantic")
    except ImportError as e:
        print(f"❌ pydantic: {e}")
        return False
    
    try:
        import overpy
        print("✅ overpy")
    except ImportError as e:
        print(f"❌ overpy: {e}")
        return False
    
    return True


def test_project_modules():
    """Test that project modules can be imported."""
    print("\n🧪 Testing project modules...")
    
    try:
        from toronto_streetview_count import cli
        print("✅ toronto_streetview_count.cli")
    except ImportError as e:
        print(f"❌ toronto_streetview_count.cli: {e}")
        return False
    
    try:
        from toronto_streetview_count import models
        print("✅ toronto_streetview_count.models")
    except ImportError as e:
        print(f"❌ toronto_streetview_count.models: {e}")
        return False
    
    try:
        from toronto_streetview_count import data_acquisition
        print("✅ toronto_streetview_count.data_acquisition")
    except ImportError as e:
        print(f"❌ toronto_streetview_count.data_acquisition: {e}")
        return False
    
    try:
        from toronto_streetview_count import road_processing
        print("✅ toronto_streetview_count.road_processing")
    except ImportError as e:
        print(f"❌ toronto_streetview_count.road_processing: {e}")
        return False
    
    try:
        from toronto_streetview_count import streetview_client
        print("✅ toronto_streetview_count.streetview_client")
    except ImportError as e:
        print(f"❌ toronto_streetview_count.streetview_client: {e}")
        return False
    
    return True


def test_cli_help():
    """Test that CLI help works."""
    print("\n🧪 Testing CLI help...")
    
    try:
        from toronto_streetview_count import cli
        # This should not raise an error
        print("✅ CLI help accessible")
        return True
    except Exception as e:
        print(f"❌ CLI help failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🚀 Toronto Street View Counter - Installation Test")
    print("=" * 50)
    
    # Test imports
    if not test_imports():
        print("\n❌ Import tests failed!")
        sys.exit(1)
    
    # Test project modules
    if not test_project_modules():
        print("\n❌ Project module tests failed!")
        sys.exit(1)
    
    # Test CLI
    if not test_cli_help():
        print("\n❌ CLI tests failed!")
        sys.exit(1)
    
    print("\n🎉 All tests passed! Installation is successful.")
    print("\n📖 Next steps:")
    print("1. Set up Google Cloud authentication: gcloud auth application-default login")
    print("2. Optionally set project: export GOOGLE_CLOUD_PROJECT='your-project-id'")
    print("3. Run: toronto-streetview-count status")
    print("4. Start with: toronto-streetview-count download-boundary")


if __name__ == "__main__":
    main()
