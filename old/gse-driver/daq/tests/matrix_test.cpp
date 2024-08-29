#include "../matrix.h"
#include <gtest/gtest.h>
#include <chrono>

/// @brief test creating a matrix and using at.
TEST(TestMatrix, testBasic)
{
    Matrix<int> mat(5, 5);

    ASSERT_THROW(mat.at(5, 0), std::runtime_error);
    ASSERT_THROW(mat.at(0, 5), std::runtime_error);

    ASSERT_NO_THROW(mat.at(3, 3));

    mat.at(3, 3) = 1;
    ASSERT_EQ(mat.at(3, 3), 1);

    int var = mat.at(3, 3);
    ASSERT_EQ(var, mat.at(3, 3));

    mat.reserve(2, 2);
    ASSERT_THROW(mat.at(2, 2), std::runtime_error);
}

/// @brief show just how much faster a matrix is than a 2d vector.
TEST(TestMatrix, testBenchmark)
{
    auto prev = std::chrono::system_clock::now();
    const auto SIZE = 5000;
    std::vector<std::vector<int>> vec;
    vec.resize(SIZE, std::vector<int>(SIZE));
    for (size_t i = 0; i < SIZE; i++)
    {
        for (size_t j = 0; j < SIZE; j++)
        {
            vec[i][j] = 0;
        }
    }
    auto next = std::chrono::system_clock::now();
    auto vec_time = next - prev;

    auto prev_ = std::chrono::system_clock::now();
    Matrix<int> mat(SIZE, SIZE);
    for (size_t i = 0; i < SIZE; i++)
    {
        for (size_t j = 0; j < SIZE; j++)
        {
            mat.at(i, j) = 0;
        }
    }
    auto next_ = std::chrono::system_clock::now();
    auto mat_time = next_ - prev_;

    ASSERT_LE(mat_time.count(), vec_time.count());
}
