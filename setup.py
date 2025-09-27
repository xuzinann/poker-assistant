from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="poker-assistant",
    version="0.1.0",
    author="Poker Assistant Team",
    description="Real-time GTO and exploitative poker strategy assistant",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/poker-assistant",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.10",
    install_requires=[
        "mss>=9.0.1",
        "Pillow>=10.0.0",
        "pytesseract>=0.3.10",
        "opencv-python>=4.8.0",
        "sqlalchemy>=2.0.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "PyQt5>=5.15.0",
        "watchdog>=3.0.0",
        "pyyaml>=6.0",
        "loguru>=0.7.0",
    ],
    entry_points={
        "console_scripts": [
            "poker-assistant=main:main",
        ],
    },
)