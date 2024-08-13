#include "client/cpp/synnax.h"
// just some test code to test the synnax library include and bazel run
#include <string>
#include <iostream>

using namespace std;

int main() {
    string input;
    cout << "Enter a string: ";
    getline(cin, input);
    cout << "You entered: " << input << endl;
    return 0;
}