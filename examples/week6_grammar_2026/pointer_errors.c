int main() {
  int value = 7;
  int *pointer =
      value; // semantic warning: integer needs an explicit pointer cast
  int result = *value; // semantic error: only pointers may be dereferenced
  return result;
}
