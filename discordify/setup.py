from setuptools import setup

setup(
    name="discordify",
    version="0.1.0",
    packages=["discordify_module"],
    package_dir={"discordify_module": "discordify-module"},
    install_requires=["matrix-synapse>=1.90.0"],
    python_requires=">=3.8",
    extras_require={"test": ["pytest>=7.0", "pytest-asyncio>=0.21"]},
)
