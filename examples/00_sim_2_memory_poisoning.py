def format_record(name, item_id):
    return f"ID={item_id}: Name={name}"

def process_data(count):
    total = 0
    for i in range(count):
        total += i * 2
    return total

def main():
    report = format_record("TelemetryItem", 42)
    s = process_data(10
    print(f"{report} -> Sum: {s}")

if __name__ == "__main__":
    main()
