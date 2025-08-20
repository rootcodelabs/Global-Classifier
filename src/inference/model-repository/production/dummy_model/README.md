### Dummy Model
This is a dummy model with a config.pbtxt and model.py that returns a static payload everytime. This dummy model just exists in the model repository of both the testing and production servers so that when the containers start the triton servers have a reference config.pbtxt that doesn't cause them to fail.

Under no circumstances should this model be deployed