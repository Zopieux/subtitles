from setuptools import setup

setup(name='subtitles',
      version='0.1',
      description='Download subtitles from opensubtitles.org',
      classifiers=[
          'Development Status :: 3 - Alpha',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3.4',
      ],
      keywords='subtitles download opensubtitles',
      url='http://github.com/zopieux/subtitles',
      author='Alexandre Macabies',
      author_email='web+oss@zopieux.com',
      license='MIT',
      packages=['subtitles'],
      entry_points={
          'console_scripts': ['subtitles=subtitles.__main__:main'],
      },
      test_suite='nose.collector',
      tests_require=['nose'],
      include_package_data=True,
      zip_safe=False)
