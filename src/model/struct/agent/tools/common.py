def normalize_collection_info(info):
	if isinstance(info, dict):
		return info
	if isinstance(info, str) and info:
		return {"model": info}
	return {}