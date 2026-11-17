def compute_sequence(depth):
    if depth <= 0:
        return 0
    acc = sum((i * 3) + 1 for i in range(depth))
    return acc + compute_sequence(depth - 1)

def validate_limits(val):
    max_val = 1000
    if val > max_val
        return False
    return True

def main():
    r = compute_sequence(5)
    valid = validate_limits(r)
    print(f"Result: {r}, Valid: {valid}")

if __name__ == "__main__":
    main()
