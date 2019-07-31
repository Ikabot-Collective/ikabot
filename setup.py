import setuptools

setuptools.setup(
	name="ikabot",
	version="5.2.5",
	author="physics-sp",
	description="A bot for ikariam",
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

