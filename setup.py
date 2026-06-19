from pathlib import Path

from setuptools import find_packages, setup


PROJECT_ROOT = Path(__file__).resolve().parent
README_PATH = PROJECT_ROOT / "README.md"


setup(
    name="career-copilot-premium",
    version="0.1.0",
    description="Cross-platform AI interview copilot.",
    long_description=README_PATH.read_text(encoding="utf-8"),
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=("tests", "tests.*")),
    include_package_data=True,
    package_data={
        "desktop_app": ["config/*.json"],
        "web_app": ["templates/*.html", "static/css/*.css", "static/js/*.js"],
    },
    install_requires=[
        "pypdf>=4.2,<6.0",
        "pdfminer.six>=20221105,<20260000",
        "cryptography>=43.0,<45.0",
        "Flask>=3.0,<4.0",
        "qrcode[pil]>=7.4,<9.0",
        "segno>=1.6.0,<2.0",
        "sounddevice>=0.4.7,<1.0",
        "soundfile>=0.12,<1.0",
    ],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "career-copilot=desktop_app.main:main",
        ],
    },
    extras_require={
        "dev": ["pytest>=8.3,<9.0"],
        "audio": ["sounddevice>=0.4.7,<1.0"],
        "gui": ["PySide6>=6.7,<7.0"],
        "hotkeys": ["keyboard>=0.13.5,<1.0"],
        "stt": ["openai-whisper>=20231117"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)