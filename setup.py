from setuptools import setup, find_packages

setup(
    name="multibeam_tools",
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests", "*.test*", ]),
    package_data={
        "": [
            'media/*.*',
        ],
    },
    zip_safe=False,
    setup_requires=[
        "setuptools",
        "wheel",
    ],
    install_requires=[
        "PySide2",
        "utm",
        "scipy",
        "numpy",
        "matplotlib"
    ],
    python_requires='>=3.5',
    description="Multibeam tools for Sea Acceptance Trials or Quality Assessment Testing.",
    keywords="hydrography ocean mapping",
    url="https://github.com/MBAdv/multibeam_tools",
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Scientific/Engineering :: GIS',
    ],
)