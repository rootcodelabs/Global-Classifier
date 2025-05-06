try:
    import os
    from loguru import logger
    from constants import TRAINING_LOGS_PATH
    print("INIT STARTED MAIN.PY")
    logger.add(sink=TRAINING_LOGS_PATH)
    logger.info("INIT STARTED MAIN.PY")

    from model_trainer import ModelTrainer
    import json

    print("INIT STARTED MAIN.PY - Log recorded")

    logger.info("PROCESS STARTED MAIN.PY")
    print("PROCESS STARTED MAIN.PY - Log recorded")
    
    cookie = str(os.environ.get('cookie'))
    new_model_id = int(os.environ.get('newModelId'))
    old_model_id = int(os.environ.get('modelId'))
    update_type = str(os.environ.get('updateType'))
    prev_deployment_env = str(os.environ.get('previousDeploymentEnv'))
    progress_session_id = int(os.environ.get('progressSessionId'))
    deployment_env = str(os.environ.get('deploymentEnv'))
    model_details = json.loads(os.environ.get('modelDetails'))

    logger.info(f"COOKIE - {cookie}")
    print(f"COOKIE - {cookie} - Log recorded")

    logger.info(f"OLD MODEL ID {old_model_id}")
    print(f"OLD MODEL ID {old_model_id} - Log recorded")

    logger.info(f"NEW MODEL ID - {new_model_id}")
    print(f"NEW MODEL ID - {new_model_id} - Log recorded")

    logger.info(f"UPDATE TYPE  - {update_type}")
    print(f"UPDATE TYPE  - {update_type} - Log recorded")

    logger.info(f"PREVIOUS DEPLOYMENT ENV - {prev_deployment_env}")
    print(f"PREVIOUS DEPLOYMENT ENV - {prev_deployment_env} - Log recorded")

    logger.info(f"PROGRESS SESSION ID - {progress_session_id}")
    print(f"PROGRESS SESSION ID - {progress_session_id} - Log recorded")

    logger.info(f"MODEL DETAILS - {model_details}")
    print(f"MODEL DETAILS - {model_details} - Log recorded")

    logger.info(type(model_details))
    print(f"MODEL DETAILS TYPE - {type(model_details)} - Log recorded")

    logger.info(f"ENTERING MODEL TRAINER SCRIPT FOR MODEL ID  - {old_model_id}")
    print(f"ENTERING MODEL TRAINER SCRIPT FOR MODEL ID  - {old_model_id} - Log recorded")

    trainer = ModelTrainer(cookie=cookie, new_model_id=new_model_id,
                        old_model_id=old_model_id, prev_deployment_env=prev_deployment_env,
                        update_type=update_type, progress_session_id=progress_session_id, 
                        current_deployment_platform=deployment_env, model_details=model_details)
    trainer.train()

    logger.info("TRAINING SCRIPT COMPLETED")
    print("TRAINING SCRIPT COMPLETED - Log recorded")

except Exception as e:
    logger.info(f"Error in MAIN.PY : {e}")
    print(f"Error in MAIN.PY - Log recorded")
