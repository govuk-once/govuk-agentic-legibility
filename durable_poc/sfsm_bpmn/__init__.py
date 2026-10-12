"""Non-executable, multi-process BPMN visualisation of SFSM definitions."""

from .converter import UnsupportedSFSM, convert_sfsm

__all__ = ["UnsupportedSFSM", "convert_sfsm"]
