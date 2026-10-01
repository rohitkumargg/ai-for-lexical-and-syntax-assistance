int main() {
  int value = 7;
  int result = *value; // error: value is not a pointer
  return result;
}