def build_prompt(template: str, schema_text: str, input_text: str) -> str:
    return template.replace("{{schema}}", schema_text).replace("{{input_text}}", input_text)

