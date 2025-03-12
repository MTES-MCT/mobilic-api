DEFAULT_KEY = "default"


def resolve_variables(dict_var, business):
    res_dict = {}
    for key, val in dict_var.items():
        if isinstance(val, dict):
            for transport_type, val2 in val.items():
                if transport_type != business.transport_type.name:
                    continue
                if isinstance(val2, dict):
                    default_value = None
                    for business_type, val3 in val2.items():
                        if business_type == DEFAULT_KEY:
                            default_value = val3
                            continue
                        if business_type != business.business_type.name:
                            continue
                        res_dict[key] = val3
                        break
                    if key not in res_dict and default_value:
                        res_dict[key] = default_value
                else:
                    res_dict[key] = val2
        else:
            res_dict[key] = val
    return res_dict
