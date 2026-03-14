// Compute factorial in Tiny C
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

int main() {
    int res = factorial(5);
    poke(0x80, res); // 5! = 120
    return 0;
}
