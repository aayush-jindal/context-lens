from setuptools import setup, find_packages

setup(
    name="context-lens",
    version="0.1.0",
    description="Token waste analyzer for Cursor and Claude Code sessions",
    py_modules=["analyze"],
    packages=find_packages(),
    install_requires=["tiktoken"],
    python_requires=">=3.9",
    entry_points={
        "console_scripts": [
            "context-lens=analyze:main",
        ],
    },
)
