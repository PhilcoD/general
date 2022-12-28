def d4_cleaning_inputs(text):
    cleaning_pairs_dict = dict()
    split_text=text.splitlines()
    for i in range(len(split_text)):
        pair_split = split_text[i].find(",")
        hold_pair_1 = split_text[i][:pair_split]
        hold_pair_2 = split_text[i][pair_split+1:]
        pair_1_split = hold_pair_1.find("-")
        pair_2_split = hold_pair_2.find("-")
        
        cleaning_pairs_dict[str(i)] = {
            "elf_1_start": hold_pair_1[:pair_1_split],
            "elf_1_end": hold_pair_1[pair_1_split+1:],
            "elf_2_start": hold_pair_2[:pair_2_split],
            "elf_2_end": hold_pair_2[pair_2_split+1:],
        }
    return cleaning_pairs_dict

def d4_fully_contained_pairs(cleaning_pairs_dict):
    overlapping_pairs = []
    
    for i in list(cleaning_pairs_dict.keys()):
        elf_1_start = int(cleaning_pairs_dict[i]["elf_1_start"])
        elf_1_end = int(cleaning_pairs_dict[i]["elf_1_end"])
        elf_2_start = int(cleaning_pairs_dict[i]["elf_2_start"])
        elf_2_end = int(cleaning_pairs_dict[i]["elf_2_end"])
        
        if elf_1_start>=elf_2_start and elf_2_end>=elf_1_end:
            overlapping_pairs.append(i)
        elif elf_2_start>=elf_1_start and elf_1_end>=elf_2_end:
            overlapping_pairs.append(i)
    return overlapping_pairs

def d4_overlapping_pairs(cleaning_pairs_dict):
    overlapping_pairs = []
    
    for i in list(cleaning_pairs_dict.keys()):
        elf_1_start = int(cleaning_pairs_dict[i]["elf_1_start"])
        elf_1_end = int(cleaning_pairs_dict[i]["elf_1_end"])
        elf_2_start = int(cleaning_pairs_dict[i]["elf_2_start"])
        elf_2_end = int(cleaning_pairs_dict[i]["elf_2_end"])
        
        elf_1_range = list(range(elf_1_start,elf_1_end+1))
        elf_2_range = list(range(elf_2_start,elf_2_end+1))
        
        if len(set(elf_1_range).intersection(elf_2_range))>0:
            overlapping_pairs.append(i)
    return overlapping_pairs

def d5_instruction_inputs(input_text):
    split_text = input_text.splitlines()
    i = 0
    instruction_dict = dict()

    for instruction in split_text:
        move_loc = instruction.find("move")
        from_loc = instruction.find("from")
        to_loc = instruction.find("to")
        crate_num = instruction[move_loc+len("move"):from_loc].strip()
        stack_from = instruction[from_loc+len("from"):to_loc].strip()
        stack_to = instruction[to_loc+len("to"):].strip()

        instruction_dict[f"{str(i)}"] = {"crate_num": crate_num,
                                         "stack_from": stack_from,
                                         "stack_to": stack_to}
        i = i+1
    return instruction_dict

def d5_crate_move(crate_arrangement: dict, instructions: dict):
    for i in instructions.keys():
        crate_num = instructions[i]["crate_num"]
        stack_to = instructions[i]["stack_to"]
        stack_from = instructions[i]["stack_from"]
    
        crates_to_move = crate_arrangement[stack_from][-int(crate_num):]

        crate_arrangement[stack_to].extend(list(reversed(crates_to_move)))
        crate_arrangement[stack_from] = crate_arrangement[stack_from][:len(crate_arrangement[stack_from])-int(crate_num)]    
        
    return crate_arrangement

def d5_crate_move_at_once(crate_arrangement: dict, instructions: dict):
    for i in instructions.keys():
        crate_num = instructions[i]["crate_num"]
        stack_to = instructions[i]["stack_to"]
        stack_from = instructions[i]["stack_from"]
    
        crates_to_move = crate_arrangement[stack_from][-int(crate_num):]

        crate_arrangement[stack_to].extend(crates_to_move)
        crate_arrangement[stack_from] = crate_arrangement[stack_from][:len(crate_arrangement[stack_from])-int(crate_num)]    
        

        
    return crate_arrangement

def d6_marker_start(text, marker_length):
    marker = []
    for i in range(len(text)-marker_length):
        sub_string = text[i:i+marker_length]
        if len(set(sub_string))==marker_length:
            marker.append(i+marker_length)
    return marker[0]

def d8_inputs(input_string):
    input_string_splitlines = input_string.splitlines()
    number_of_cols = len(input_string_splitlines[0])
    number_of_rows = len(input_string_splitlines)
    manipulated_input = []
    for i in range(number_of_cols):
        manipulated_input.append(list(input_string_splitlines[i]))
    return manipulated_input, number_of_cols, number_of_rows

def d8_visible_trees_outside(manipulated_input, number_of_rows, number_of_cols):

    visible_trees = []
    for i in range(number_of_rows):
        if i == 0 or i == number_of_rows-1:
            continue

        for j in range(number_of_cols):
            if j == 0 or j == number_of_cols-1:
                continue

            tree_height = manipulated_input[i][j]
            see_tree = False

            trees_to_left = manipulated_input[i][:j]
            trees_to_right = manipulated_input[i][j+1:]
            trees_column = [x[j] for x in manipulated_input]
            trees_column
            trees_above = trees_column[:i]
            trees_below = trees_column[i+1:]

            if tree_height > max(trees_to_left):
                see_tree = True
            if tree_height > max(trees_to_right):
                see_tree = True
            if tree_height > max(trees_above):
                see_tree = True
            if tree_height > max(trees_below):
                see_tree = True

            if see_tree:
                visible_trees.append([j,i])

    total_visible_trees = len(visible_trees) + 2*(number_of_rows + number_of_cols) - 4
   
    return total_visible_trees

def d8_visible_trees_inside(manipulated_input, number_of_rows, number_of_cols):
    scenic_tree = 0
    for i in range(number_of_rows):
        for j in range(number_of_cols):

            tree_height = manipulated_input[i][j]

            trees_to_left = manipulated_input[i][:j]
            trees_to_left.reverse()
            trees_to_right = manipulated_input[i][j+1:]
            trees_column = [x[j] for x in manipulated_input]
            trees_column
            trees_above = trees_column[:i]
            trees_above.reverse()
            trees_below = trees_column[i+1:]

            visible_trees_left = []
            visible_trees_right = []
            visible_trees_above = []
            visible_trees_below = []

            for k in trees_to_left:
                visible_trees_left.append(k)
                if k >= tree_height:
                    break
            for k in trees_to_right:
                visible_trees_right.append(k)
                if k >= tree_height:
                    break
            for k in trees_above:
                visible_trees_above.append(k)
                if k >= tree_height:
                    break
            for k in trees_below:
                visible_trees_below.append(k)
                if k >= tree_height:
                    break

            tree_scenic_value = len(visible_trees_left) * len(visible_trees_right) * len(visible_trees_above) * len(visible_trees_below)
            if tree_scenic_value >= scenic_tree:
                scenic_tree = tree_scenic_value
    return scenic_tree


def d10_inputs(input_txt_path):
    
    with open(input_txt_path) as f:
        input_string = f.read()
    splitlines = input_string.splitlines()
    commands = []
    for i in range(len(splitlines)):
        if splitlines[i].find("addx") == 0:
            commands.append([int(splitlines[i][5:]), 2])
        else:
            commands.append([0, 1])

    return commands

def d10_signal_strength(commands):
    v = 1
    cycles = 0
    signal_strength = 0
    cycle_list = [20, 60, 100, 140, 180, 220]
    for i in commands:
        for j in range(i[1]):
            cycles += 1
            if cycles in cycle_list:
                signal_strength += v*cycles
        v += i[0]

    return signal_strength   

def d10_system_image(commands):
    sprite = "###"
    sprite_position = sprite + 37*"."
    sprite_position

    v = 1
    cycles = 0
    signal_strength = 0
    picture = ""
    for i in commands:
        for j in range(i[1]):
            cycles += 1
            if sprite_position[(cycles%40)-1] == "#":
                picture += "#"
            if sprite_position[(cycles%40)-1] != "#":
                picture += "."
        v += i[0]
        start_of_string = "."*(v-1) + "###"
        end_of_string = "."*(40-len(start_of_string))
        sprite_position = start_of_string + end_of_string

    system_output=  ""
    for i in range(int(len(picture)/40)):
        system_output += picture[i*40:(i*40)+40] + "\n"
    print(system_output)