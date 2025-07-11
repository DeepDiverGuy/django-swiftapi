def run_new_environment(obj_to_return, codes, extra_globals=None):
    globals_dict = globals().copy()
    if extra_globals:
        globals_dict.update(extra_globals)
    exec(codes, globals_dict)
    return globals_dict[obj_to_return]

