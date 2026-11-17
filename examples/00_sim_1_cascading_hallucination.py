def compute_factorial(n):
    if n <= 1:
        return 1
    return n * compute_factorial(n - 1)

def calculate_discount(price, percent):
    if percent < 0
        return price
    discount = (price * percent) // 100
    return price - discount

def main():
    p = 250
    f = compute_factorial(5)
    final_p = calculate_discount(p, 10)
    print(f"Factorial: {f}, Final: {final_p}")

if __name__ == "__main__":
    main()
