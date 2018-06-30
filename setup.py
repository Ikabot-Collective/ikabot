import setuptools

setuptools.setup(
	name="ikabot",
	version="0.1.12",
	author="santipcn",
	description="A bot for ikariam",
	url="https://github.com/santipcn/ikabot",
	packages=setuptools.find_packages(),
	install_requires=[
		  'requests',
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
