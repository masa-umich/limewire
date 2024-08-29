#include "client/cpp/synnax.h"
// just some test code to test the synnax library include and bazel run
#include <string>
#include <iostream>

using namespace std;

int main() {
    string test;
    cout << "Enter a string: ";
    cin >> test;
    cout << "You entered: " << test << endl;
    return 0;
}