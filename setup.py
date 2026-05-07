from setuptools import setup

setup(
    name="butcher",
    version="1.0.0",
    description="Surgical web scraper for high-fidelity data intelligence",
    url="https://github.com/project-hellhound/butcher",
    py_modules=["butcher"],
    python_requires=">=3.10",
    install_requires=[
        "aiohttp>=3.9.0",
        "beautifulsoup4>=4.12.0",
        "lxml>=5.0.0",
        "playwright>=1.40.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "butcher=butcher:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Intended Audience :: Information Technology",
        "Topic :: Security",
        "Operating System :: OS Independent",
    ],
)
