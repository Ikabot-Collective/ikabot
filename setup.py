import setuptools

with open("README.md", "r") as fh:
	long_description = fh.read()

setuptools.setup(
	name="ikabot",
	version="4.3.2",
	author="physics-sp",
	description="A bot for ikariam",
	long_description=long_description,
	long_description_content_type="text/markdown",
	url="https://github.com/physics-sp/ikabot",
	include_package_data=True,
	packages=setuptools.find_packages(),
	install_requires=[
		  'requests',
		  'pycryptodome'
	],
	entry_points = {
		'console_scripts': ['ikabot=ikabot.command_line:main'],
	},
	classifiers=(
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: MIT License",
		"Operating System :: POSIX :: Linux",
	),
)
