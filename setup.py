import setuptools

setuptools.setup(
	name="ikabot",
	version="6.4.9",
	author="physics-sp",
	author_email="physics-sp@protonmail.com",
	license='MIT',
	description="A bot for ikariam",
	url="https://github.com/physics-sp/ikabot",
	include_package_data=True,
	packages=setuptools.find_packages(),
	install_requires=[
		  'requests',
		  'requests[socks]',
		  'cryptography',
		  'psutil'
	],
	entry_points = {
		'console_scripts': ['ikabot=ikabot.command_line:main'],
	},
	classifiers=[
		"Programming Language :: Python :: 3",
		"License :: OSI Approved :: MIT License"
        ],
)

