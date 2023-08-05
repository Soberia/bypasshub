from importlib.metadata import version, metadata

__version__ = version(__package__)
__homepage__ = metadata(__package__)["Project-URL"].split()[-1]
