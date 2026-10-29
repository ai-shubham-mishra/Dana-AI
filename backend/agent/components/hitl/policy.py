from agent.components.hitl.ask_user import ASK_USER_TOOL
from agent.tools.training.start_job import START_TRAINING_JOB_TOOL

INTERRUPT_ON = {
    ASK_USER_TOOL: {"allowed_decisions": ["respond"]},
    START_TRAINING_JOB_TOOL: {"allowed_decisions": ["approve", "edit", "reject"]},
}
