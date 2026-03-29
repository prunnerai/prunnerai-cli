from setuptools import setup, find_packages

setup(
    name="prunnerai-cli",
    version="3.2.0",
    description="PrunnerAI CLI — Sovereign AI command & control for your local machine",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    author="PrunnerAI",
    url="https://prunerai.lovable.app",
    packages=find_packages(),
    python_requires=">=3.7",
    install_requires=[],
    extras_require={
        "ai": ["torch", "transformers", "huggingface_hub"],
        "gui": ["fastapi", "uvicorn[standard]"],
    },
    entry_points={
        "console_scripts": [
            "prunnerai=prunnerai.cli:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
