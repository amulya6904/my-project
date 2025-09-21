"""Setup configuration for bank statement processor."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="bank-statement-processor",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A CLI tool to extract transaction data from Indian bank PDF statements",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/bank-statement-processor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Intended Audience :: Financial and Insurance Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Office/Business :: Financial",
        "Topic :: Text Processing",
        "Topic :: Utilities",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    extras_require={
        "dev": [
            "black>=23.0.0",
            "flake8>=6.0.0", 
            "mypy>=1.0.0",
            "isort>=5.0.0",
            "pytest>=7.0.0",
            "pytest-cov>=4.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "bank-statement-processor=src.cli:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.md", "*.txt", "*.yml", "*.yaml"],
    },
    zip_safe=False,
    project_urls={
        "Bug Reports": "https://github.com/yourusername/bank-statement-processor/issues",
        "Source": "https://github.com/yourusername/bank-statement-processor",
        "Documentation": "https://github.com/yourusername/bank-statement-processor/README.md",
    },
)