import json

with open('blank.json','r+') as f:
	data = json.load(f)

data['ops_profile_params']['obs_params']['targets'] = []

with open('blank.json','w') as f:
	json.dump(data, f, indent = 4)


