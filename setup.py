import os
import sys

from setuptools import setup


PACKAGE_DIR = "lcpvian"
BASEPATH = os.path.dirname(__file__)
MODULE_PATH = os.path.join(BASEPATH, PACKAGE_DIR)

SKIPS: set[str] = {"__main__.py", "deploy.py", "nomypy.py"}

# use build_ext to do mypy c compilation
if not any(a.endswith("setup.py") for a in sys.argv) or "build_ext" in sys.argv:
    from mypyc.build import mypycify

    if "build_ext" in sys.argv and "--inplace" not in sys.argv:
        sys.argv.append("--inplace")

    files = []
    for i in os.listdir(MODULE_PATH):
        if i not in SKIPS and i.endswith(".py"):
            files.append(os.path.join(MODULE_PATH, i))
    ext_modules = mypycify(files, multi_file=False, verbose=True, separate=False)

else:
    ext_modules = []

# with open("requirements.txt") as f:
#     REQUIRED = [
#         i.split(" #")[0].strip()
#         for i in f.read().splitlines()
#         if i
#         and not i.strip().startswith("#")
#         and not i.strip().startswith("-r")
#         and "git+" not in i
#     ]
#     REQUIRED.append(
#         "backports.zoneinfo @ http://github.com/morganwahl/zoneinfo/tarball/master#egg=zoneinfo-0.2.1"
#     )


def read(fname):
    """
    Helper to read README
    """
    return open(os.path.join(BASEPATH, fname)).read().strip()


kwargs = dict(
    name=PACKAGE_DIR,
    version="0.0.1",
    description="corpus linguistics app",
    long_description=read("README.md"),
    long_description_content_type="text/markdown",
    url="https://gitlab.uzh.ch/LiRI/projects/lcpvian",
    author="Danny McDonald",
    include_package_data=True,
    zip_safe=False,
    packages=[PACKAGE_DIR],
    package_data={
        PACKAGE_DIR: ["lcpvian/py.typed"],
    },
    author_email="mcddjx@gmail.com",
    license="MIT",
    keywords=["corpus", "linguistics"],
    # install_requires=REQUIRED,
)

if ext_modules:
    kwargs["ext_modules"] = ext_modules

setup(**kwargs)
