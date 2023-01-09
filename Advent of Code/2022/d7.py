def d7_inputs(input_txt_path):
    with open(input_txt_path) as f:
        input_string = f.read()
    splitlines = input_string.splitlines()
    
    current_path = []
    current_path_full = []
    directories = {}
    for line in splitlines:
        if "$ cd " in line:
            if "$ cd .." in line:
                current_path.pop(-1)
                current_path_full.pop(-1)
            else:
                current_path.append(line[len("$ cd")+1:])
                current_path_str = "_".join(current_path)
                current_path_full.append(current_path_str)
        elif "$ ls" in line:
            directories[current_path_str] = {"directories": [],
                                                   "files": [],
                                            "total_size": 0}
        elif line[:4] == "dir ":
            directories[current_path_str]["directories"].append("_".join(current_path) + "_" + line[4:])
        else:
            space = line.find(" ")
            for cur in current_path_full:
                directories[cur]["files"].append(int(line[:space]))
    
    for i in directories.keys():
        directories[i]["total_size"] = sum(directories[i]["files"])
    
    return directories

def small_directories_sum(directories, min_size=100000):
    return sum([directories[i]["total_size"] for i in directories.keys() if directories[i]["total_size"]<=100000])

def directory_to_delete(directories, total_space=70000000, space_required=30000000):
    needed_space = space_required - (total_space-directories["/"]["total_size"])
    big_directories = [directories[i]["total_size"] for i in directories.keys() if directories[i]["total_size"]>=needed_space]
    big_directories.sort()
    return big_directories[0]