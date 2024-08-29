#pragma once
#include <cstddef>
#include <stdexcept>
#include <memory>

/// @brief a 2D matrix that uses a 1D vector under the hood.
template <typename T>
class Matrix
{
public:
    Matrix() {}

    Matrix(size_t n_, size_t m_)
        : n(n_), m(m_)
    {
        flat_data = std::vector<T>(n * m);
    }

    void reserve(size_t i, size_t j)
    {
        n = i;
        m = j;
        if (flat_data)
        {
            delete[] flat_data;
        }
        flat_data = new T[n * m];
    }

    T &at(size_t i, size_t j)
    {
        if (i >= n || j >= m)
        {
            throw std::runtime_error("Out-of-bounds error on Matrix; attempting to access (" +
                                     std::to_string(i) + "," + std::to_string(j) +
                                     ") on a matrix of size (" +
                                     std::to_string(n) + "," + std::to_string(m) + ")");
        }
        return flat_data.data()[i * m + j];
    }

    T *data()
    {
        return flat_data.data();
    }

    std::vector<T> &vec()
    {
        return flat_data;
    }

    std::pair<size_t, size_t> size()
    {
        return {n, m};
    }

    void clear() {
        flat_data.clear();
    }

private:
    size_t n;
    size_t m;
    std::vector<T> flat_data;
};