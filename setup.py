import setuptools

from ikabot.config import IKABOT_VERSION

setuptools.setup(
    name="ikabot",
    version=IKABOT_VERSION,
    author="physics-sp",
    author_email="physics-sp@protonmail.com",
    license="MIT",
    description="A Python-based bot designed for automating tasks in the game Ikariam",
    url="https://github.com/Ikabot-Collective/ikabot",
    include_package_data=True,
    packages=setuptools.find_packages(),
    install_requires=["requests", "requests[socks]", "cryptography", "psutil"],
    entry_points={
        "console_scripts": ["ikabot=ikabot.command_line:main"],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
    ],
)
