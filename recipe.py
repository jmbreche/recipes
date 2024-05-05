import markdown2
import pdfkit
import re
import sys

from fractions import Fraction


def read(text):
    text = re.sub(r"\n\s*", "", text)

    while "<" in text:
        tag = re.match(r"<([^<>]+)>", text).group(1)

        if tag[-1] == "/":
            tag = tag[:-1]

            content = None

            skip = len(tag) + 3
        else:
            content = re.match(rf"<{tag}>(.*?)</{tag}>", text)

            skip = content.end()

            content = content.group(1)

        text = text[skip:]

        yield tag, content


def define(content):
    if content is None:
        return []
    elif not "<" in content:
        return [content]
    else:
        tag, content = next(read(content))

        return [tag] + define(content)


def mixed_fraction(amnt):
    number = float(amnt)

    integer_part = int(number)
    
    fractional_part = Fraction(number - integer_part).limit_denominator()
    
    if fractional_part.numerator == 0:
        return str(integer_part)
    elif integer_part == 0:
        return f"{fractional_part.numerator}/{fractional_part.denominator}"
    else:
        return f"{integer_part} {fractional_part.numerator}/{fractional_part.denominator}"


def convert(amnt, unit):
    if units[unit]:
        tag, instructions = next(read(units[unit]))

        if tag == "IF":
            while True:
                instructions = instructions.split("<THEN>", maxsplit=1)

                tag, content = next(read(instructions[0]))

                if (tag == "GT" and float(amnt) > float(content)) or (tag == "LT" and float(amnt) < float(content)):
                    tag, content = next(read(instructions[1]))

                    amnt = str(float(amnt) * float(content))
                    unit = tag

                    return convert(amnt, unit)
                elif "<ELIF>" in instructions[1]:
                    instructions = instructions[1].split("<ELIF>", maxsplit=1)[1]
                else:
                    break

    if not precise:
        amnt = str(round(float(amnt) * 4) / 4)

    return mixed_fraction(amnt), unit


definitions = {}

units = {}

servings_multiplier = None

precise = False
vague = False

markdown = ["", "\n## Cookware\n\n", "## Ingredients\n\n", "## Instructions\n\n"]

with open("dict/units.xml", "r") as file:
    txt = file.read()

for tag, content in read(txt):
    units[tag] = content

script = sys.argv[1]

with open(script, "r") as file:
    txt = file.read()

for tag, content in read(txt):
    if tag == "RECIPE":
        path = f"recipes/{content}.xml"
    elif tag == "SERVINGS":
        servings_multiplier = float(content)

        markdown[0] += f"\n- {content} Servings"
    elif tag == "PRECISE":
        precise = True
    elif tag == "REPLACE":
        content = read(content)

        before, _ = next(content)
        after, _ = next(content)

        definitions[before] = after
    elif tag == "VAGUE":
        vague = True

with open(path, "r") as file:
    txt = file.read()

for tag, content in read(txt):
    if tag == "TITLE":
        markdown[0] = f"# {content}" + markdown[0]
    elif tag == "METADATA":
        for meta_tag, meta_content in read(content):
            if meta_tag == "SERVINGS":
                servings_multiplier /= float(meta_content)
    elif tag == "COOKWARE":
        for cw_tag, cw_content in read(content):
            definition = ([cw_tag] + define(cw_content))[-1]

            definitions[cw_tag] = definition

            markdown[1] += f"- <b>{definition}</b>\n"
    elif tag == "INGREDIENTS":
        for prec_tag, prec_content in read(content):
            for ing_tag, ing_content in read(prec_content):
                definition = (["", "", ing_tag] + define(ing_content))

                markdown[2] += "- "

                if definition[-2] in units:
                    amnt = definition[-1]
                    unit = definition[-2]

                    if servings_multiplier:
                        amnt = str(float(amnt) * servings_multiplier)

                    amnt, unit = convert(amnt, unit)

                    markdown[2] += f"{amnt} {unit} - "

                    definition = definition[-3]
                else:
                    definition = definition[-1]

                if not ing_tag in definitions:
                    definitions[ing_tag] = definition
                
                if vague:
                    definitions[ing_tag] = ing_tag

                markdown[2] += f"<b>{definitions[ing_tag]}</b>\n"

            markdown[2] += "\n<!-- -->\n\n"
    elif tag == "INSTRUCTIONS":
        for key, definition in definitions.items():
            content = content.replace(f"<{key}/>", f"<b>{definition}</b>")

        for ins_tag, ins_content in read(content):
            markdown[3] += f"{ins_tag}. "

            if re.match(r"<[A-Z]>", ins_content[0:3]):
                for sub_tag, sub_content in read(ins_content):
                    markdown[3] += f"<strong>({sub_tag})</strong> {sub_content} "
            else:
                markdown[3] += ins_content

            markdown[3] += "\n"

pdfkit.from_string(
    markdown2.markdown("\n".join(markdown)), 
    "output/" + re.search(r"/([^/]+)\.\w+$", script).group(1) + ".pdf", 
    configuration=pdfkit.configuration(wkhtmltopdf="C:/Program Files/wkhtmltopdf/bin/wkhtmltopdf.exe"),
    css="style.css",
    options={
        "page-size": "Letter",
    }
)
