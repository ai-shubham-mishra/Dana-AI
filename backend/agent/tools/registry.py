from agent.tools.ml_ops.chores.check_last_job import CheckLastJobTool
from agent.tools.ml_ops.chores.check_last_model_run import CheckLastModelRunTool
from agent.tools.ml_ops.chores.check_latest_model import CheckLatestModelTool
from agent.tools.ml_ops.ml.data_prep.create_evaluators import CreateEvaluatorsTool
from agent.tools.ml_ops.ml.data_prep.list_channels import ListChannelsTool
from agent.tools.ml_ops.ml.data_prep.prepare_training_data import PrepareTrainingDataTool
from agent.tools.ml_ops.ml.data_prep.update_training_data import UpdateTrainingDataTool
from agent.tools.ml_ops.ml.training.check_job_status import CheckJobStatusTool
from agent.tools.ml_ops.ml.training.create_ml_training_job import CreateMLTrainingJobTool
from agent.tools.ml_ops.ml.training.create_training_script import CreateTrainingScriptTool
from agent.tools.ml_ops.ml.training.initiate_ml_training import InitiateMLTrainingTool
from agent.tools.ml_ops.ml.training.save_ml_assets import SaveMLAssetsTool
from agent.tools.ml_ops.ml.training.start_training_job import StartTrainingJobTool
from agent.tools.system_ops.connectors.list_channels_within_connector import ListChannelsWithinConnectorTool
from agent.tools.system_ops.connectors.list_connectors import ListConnectorsTool
from agent.tools.system_ops.hitl.ask_user import AskUserTool

# Every tool the agent can call. Each tool is defined in its own module; add new ones here.
TOOLS = [
    AskUserTool(),
    ListConnectorsTool(),
    ListChannelsWithinConnectorTool(),
    CheckLastJobTool(),
    CheckLatestModelTool(),
    CheckLastModelRunTool(),
    InitiateMLTrainingTool(),
    StartTrainingJobTool(),
    CreateMLTrainingJobTool(),
    SaveMLAssetsTool(),
    CreateTrainingScriptTool(),
    CheckJobStatusTool(),
    PrepareTrainingDataTool(),
    CreateEvaluatorsTool(),
    UpdateTrainingDataTool(),
    ListChannelsTool(),
]


def interrupt_policy(tools) -> dict:
    """Map each tool that needs a human decision to the decisions it allows."""
    return {tool.name: {"allowed_decisions": list(tool.allowed_decisions)} for tool in tools if tool.allowed_decisions}


INTERRUPT_ON = interrupt_policy(TOOLS)
