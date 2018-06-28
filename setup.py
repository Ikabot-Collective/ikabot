import setuptools

setuptools.setup(
	name="ikabot",
	version="0.1",
	author="santipcn",
	description="A bot for ikariam",
	url="https://github.com/santipcn/ikabot",
	packages=setuptools.find_packages(),
	install_requires=[
		  'requests',
	],
	classifiers=(
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: MIT License",
		"Operating System :: POSIX :: Linux",
	),
)
# https://packaging.python.org/tutorials/packaging-projects/