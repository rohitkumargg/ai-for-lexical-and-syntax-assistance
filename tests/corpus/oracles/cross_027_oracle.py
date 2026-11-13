def validate_password_length(password_str: str) -> bool:
    password_len = len(password_str)
    min_length = 8
    return password_len >= min_length

if __name__ == "__main__":
    print(validate_password_length("abc12345"))

