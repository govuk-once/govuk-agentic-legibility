"""State handler dispatch registry."""

from src.model import (
    AssignState,
    CallState,
    ChoiceState,
    EndState,
    InputState,
    InvokeState,
    OutputState,
    WaitState,
)
from src.handlers.input_handler import handle_input
from src.handlers.output_handler import handle_output
from src.handlers.call_handler import handle_call
from src.handlers.choice_handler import handle_choice
from src.handlers.assign_handler import handle_assign
from src.handlers.invoke_handler import handle_invoke
from src.handlers.wait_handler import handle_wait
from src.handlers.end_handler import handle_end

STATE_HANDLERS = {
    InputState: handle_input,
    OutputState: handle_output,
    CallState: handle_call,
    ChoiceState: handle_choice,
    AssignState: handle_assign,
    InvokeState: handle_invoke,
    WaitState: handle_wait,
    EndState: handle_end,
}
