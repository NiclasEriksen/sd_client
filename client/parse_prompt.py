from typing import Union
from client.logger import logger


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def parse_prompt(prompt) -> Union[str, list]:
    try:
        str_prompts = prompt.split("::")
        if len(str_prompts) == 1:
            return str_prompts[0]

        w_prompts = []

        current_str = ""
        for i in range(len(str_prompts)):
            if not len(str_prompts[i]):
                continue
            current_str += str_prompts[i]
            w = 1.0

            if i < len(str_prompts) - 1:
                ns = str_prompts[i+1]
                if is_number(ns.split(" ")[0]):
                    w = float(ns.split(" ")[0])
                    str_prompts[i+1] = " ".join(ns.split(" ")[1:])
                elif is_number(ns):
                    w = float(ns)
                else:
                    continue


            w_prompts.append((current_str.lstrip().rstrip(), max(0.0, w)))
            current_str = ""

        return w_prompts
    except Exception as e:
        logger.error(e)
        return prompt




if __name__ == "__main__":
    print(
        parse_prompt("a man and his dog::2 funny weather::-25.3312a piece of gum::14.1")
    )
    print(
        parse_prompt("impossible machine::2 funny weather::+25.3312   a piece of gum::-14.1 så e det tur igjen da. GUDD")
    )
    print(
        parse_prompt(":::::abc::1::2::1sadads")
    )
