"""
AI Product Hunter - Setup Configuration
"""
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="ai-product-hunter",
    version="0.1.0",
    author="Product Hunter Team",
    description="AI-powered e-commerce product discovery and supplier matching",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.10",
    install_requires=[
        "python-dotenv>=1.0.0",
        "sqlalchemy>=2.0.23",
        "httpx>=0.25.2",
        "pandas>=2.1.4",
        "sentence-transformers>=2.2.2",
        "streamlit>=1.29.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "black>=23.12.1",
            "flake8>=6.1.0",
            "mypy>=1.7.1",
        ]
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Application Frameworks",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)