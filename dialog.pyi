import abc
from _typeshed import Incomplete
from typing import NamedTuple, Union, Optional, Iterable, Any

class _VersionInfo(NamedTuple):
    major: Incomplete
    minor: Incomplete
    micro: Incomplete
    releasesuffix: Incomplete

class VersionInfo(_VersionInfo): ...

version_info: Incomplete

class error(Exception):
    message: Incomplete
    def __init__(self, message: Incomplete | None = ...) -> None: ...
    def complete_message(self) -> str: ...
    ExceptionShortDescription: str

PythonDialogException = error

class ExecutableNotFound(error):
    ExceptionShortDescription: str

class PythonDialogBug(error):
    ExceptionShortDescription: str

class ProbablyPythonBug(error):
    ExceptionShortDescription: str

class BadPythonDialogUsage(error):
    ExceptionShortDescription: str

class PythonDialogSystemError(error):
    ExceptionShortDescription: str

class PythonDialogOSError(PythonDialogSystemError):
    ExceptionShortDescription: str

class PythonDialogIOError(PythonDialogOSError):
    ExceptionShortDescription: str

class PythonDialogErrorBeforeExecInChildProcess(PythonDialogSystemError):
    ExceptionShortDescription: str

class PythonDialogReModuleError(PythonDialogSystemError):
    ExceptionShortDescription: str

class UnexpectedDialogOutput(error):
    ExceptionShortDescription: str

class DialogTerminatedBySignal(error):
    ExceptionShortDescription: str

class DialogError(error):
    ExceptionShortDescription: str

class UnableToRetrieveBackendVersion(error):
    ExceptionShortDescription: str

class UnableToParseBackendVersion(error):
    ExceptionShortDescription: str

class UnableToParseDialogBackendVersion(UnableToParseBackendVersion):
    ExceptionShortDescription: str

class InadequateBackendVersion(error):
    ExceptionShortDescription: str

class BackendVersion(metaclass=abc.ABCMeta):
    @classmethod
    @abc.abstractmethod
    def fromstring(cls, s: str) -> "BackendVersion": ...
    @abc.abstractmethod
    def __lt__(self, other: "BackendVersion") -> bool: ...
    @abc.abstractmethod
    def __le__(self, other: "BackendVersion") -> bool: ...
    @abc.abstractmethod
    def __eq__(self, other: object) -> bool: ...
    @abc.abstractmethod
    def __ne__(self, other: object) -> bool: ...
    @abc.abstractmethod
    def __gt__(self, other: "BackendVersion") -> bool: ...
    @abc.abstractmethod
    def __ge__(self, other: "BackendVersion") -> bool: ...

class DialogBackendVersion(BackendVersion):
    dotted_part: Incomplete
    rest: Incomplete
    def __init__(
        self, dotted_part_or_str: Union[list[str], str], rest: str = ...
    ) -> None: ...
    @classmethod
    def fromstring(cls, s: str) -> "DialogBackendVersion": ...
    def __lt__(self, other: "BackendVersion") -> bool: ...
    def __le__(self, other: "BackendVersion") -> bool: ...
    def __eq__(self, other: object) -> bool: ...
    def __ne__(self, other: object) -> bool: ...
    def __gt__(self, other: "BackendVersion") -> bool: ...
    def __ge__(self, other: "BackendVersion") -> bool: ...

# def widget(func): ...
# def retval_is_code(func): ...

class Dialog:
    OK: str
    CANCEL: str
    ESC: str
    EXTRA: str
    HELP: str
    DIALOG_OK: str
    DIALOG_CANCEL: str
    DIALOG_ESC: str
    DIALOG_EXTRA: str
    DIALOG_HELP: str
    DIALOG_ITEM_HELP: str
    @property
    def DIALOG_ERROR(self) -> int: ...
    DIALOGRC: str
    compat: str
    autowidgetsize: bool
    dialog_persistent_arglist: list[str]
    use_stdout: bool
    pass_args_via_file: bool
    cached_backend_version: DialogBackendVersion
    def __init__(
        self,
        dialog: str = ...,
        DIALOGRC: Optional[str] = ...,
        compat: str = ...,
        use_stdout: Optional[bool] = ...,
        *,
        autowidgetsize: bool = ...,
        pass_args_via_file: Incomplete | None = ...
    ) -> None: ...
    @classmethod
    def dash_escape(cls, args: list[str]) -> list[str]: ...
    @classmethod
    def dash_escape_nf(cls, args: list[str]) -> list[str]: ...
    def add_persistent_args(self, args: list[str]) -> None: ...
    def set_background_title(self, text: str) -> None: ...
    def setBackgroundTitle(self, text: str) -> None: ...
    def setup_debug(
        self,
        enable: bool,
        file: Optional[str] = ...,
        always_flush: bool = ...,
        *,
        expand_file_opt: bool = ...
    ) -> None: ...
    def clear(self) -> None: ...
    def backend_version(self) -> str: ...
    def maxsize(self, **kwargs: Any) -> tuple[int, int]: ...
    def buildlist(
        self,
        text: str,
        height: int = ...,
        width: int = ...,
        list_height: int = ...,
        items: Iterable[tuple[str, str, Union[bool, int, str]]] = ...,
        **kwargs: Any
    ) -> tuple[str, list[str]]: ...
    def calendar(
        self,
        text: str,
        height: Optional[int] = ...,
        width: int = ...,
        day: int = ...,
        month: int = ...,
        year: int = ...,
        **kwargs: Any
    ) -> tuple[str, list[str]]: ...
    def checklist(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        list_height: Optional[int] = ...,
        choices: Iterable[tuple[str, str, Union[bool, int, str]]] = ...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def form(
        self,
        text: str,
        elements: list[tuple[str, int, int, str, int, int, int, int]],
        height: int = ...,
        width: int = ...,
        form_height: int = ...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def passwordform(
        self,
        text: str,
        elements: list[tuple[str, int, int, str, int, int, int, int]],
        height: int = ...,
        width: int = ...,
        form_height: int = ...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def mixedform(
        self,
        text: str,
        elements: list[tuple[str, int, int, str, int, int, int, int]],
        height: int = ...,
        width: int = ...,
        form_height: int = ...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def dselect(
        self, filepath: str, height: int = ..., width: int = ..., **kwargs: Any
    ) -> tuple[str, str]: ...
    def editbox(self, filepath: str, height: int = ..., width: int = ...,
            **kwargs: Any) -> tuple[str, str]: ...
    def editbox_str(self, init_contents: str, *args: Any, **kwargs: Any) -> tuple[str, str]: ...
    def fselect(self, filepath: str, height: int = ..., width: int = ..., **kwargs: Any) -> tuple[str, str]: ...
    def gauge_start(
        self,
        text: str = ...,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        percent: int = ...,
        **kwargs: Any
    ) -> None: ...
    def gauge_update(
            self, percent: int, text: str = ..., update_text: bool = ...
    ) -> None: ...
    def gauge_iterate(*args: Any, **kwargs: Any) -> None: ...
    def gauge_stop(self) -> str: ...
    def infobox(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def inputbox(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        init: str = ...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def inputmenu(
        self,
        text: str,
        height: int = ...,
        width: Optional[int] = ...,
        menu_height: Optional[int] = ...,
        choices: list[tuple[str, str]]=...,
        **kwargs: Any
    ) -> tuple[str, str, str]: ...
    def menu(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        menu_height: Optional[int] = ...,
        choices: list[tuple[str, str]]=...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def mixedgauge(
        self,
        text: str,
        height: int = ...,
        width: int = ...,
        percent: int = ...,
        elements: list[tuple[str, str]]=...,
        **kwargs: Any
    ) -> str: ...
    def msgbox(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def pause(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        seconds: int = ...,
        **kwargs: Any
    ) -> str: ...
    def passwordbox(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        init: str = ...,
        **kwargs: Any
    ) -> str: ...
    def progressbox(
        self,
        file_path: Optional[str] = ...,
        file_flags: int=...,
        fd: Optional[int] = ...,
        text: Optional[str] = ...,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def programbox(
        self,
        file_path: Optional[str] = ...,
        file_flags: int=...,
        fd: Optional[int] = ...,
        text: Optional[str] = ...,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def radiolist(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        list_height: Optional[int] = ...,
        choices: list[tuple[str, str, Union[str, bool, int]]]=...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def rangebox(
        self,
        text: str,
        height: int = ...,
        width: int = ...,
        min: Optional[int] = ...,
        max: Optional[int] = ...,
        init: Optional[int] = ...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def scrollbox(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def tailbox(
        self,
        filepath: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def textbox(
        self,
        filepath: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
    def timebox(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        hour: int = ...,
        minute: int = ...,
        second: int = ...,
        **kwargs: Any
    ) -> tuple[str, list[int]]: ...
    def treeview(
        self,
        text: str,
        height: int = ...,
        width: int = ...,
        list_height: int = ...,
        nodes: list[tuple[str, str, Union[str, bool, int], int]] =...,
        **kwargs: Any
    ) -> tuple[str, str]: ...
    def yesno(
        self,
        text: str,
        height: Optional[int] = ...,
        width: Optional[int] = ...,
        **kwargs: Any
    ) -> str: ...
