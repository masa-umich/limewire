/*
* ~~~~~~~~~~~~
* masanet_tsqueue.hpp
* ~~~~~~~~~~~~
*
* Created by: E. Eidt, 07/16/2023
*
* Defines thread-safe queue used by masanet
*	(Uses scoped locks to be thread-safe, other solutions exist)
* Based on "Networking in C++" - javidx9
*
*/

#pragma once

#include <memory>
#include <thread>
#include <mutex>
#include <deque>
#include <optional>
#include <vector>
#include <iostream>
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <condition_variable>

#ifdef _WIN32
#define _WIN32_WINNT 0x0A00
#endif

	template <typename T>
	class tsqueue {
	public:

		tsqueue() = default; // default ctor
		tsqueue(const tsqueue<T>&) = delete; // don't allow copying bc it contains mutexes
		virtual ~tsqueue() { clear(); } // dtor

		// returns and maintains items at front of Queue
		const T& front() {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			return deqQueue.front(); // returns reference to first object of deque
		}

		// returns and maintains items at back of Queue
		const T& back() {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			return deqQueue.back(); // returns reference to last object of deque
		}

		void push_back(const T& item) {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			deqQueue.emplace_back(std::move(item));

			std::unique_lock<std::mutex> ul(muxBlocking);
			cvBlocking.notify_one();
		}

		void push_front(const T& item) {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			deqQueue.emplace_front(std::move(item));

			std::unique_lock<std::mutex> ul(muxBlocking);
			cvBlocking.notify_one();
		}

		// removes and returns item from front of Queue
		T pop_front() {
			std::scoped_lock lock(muxQueue);
			auto t = std::move(deqQueue.front());
			deqQueue.pop_front();
			return t;
		}

		// removes and returns item from back of Queue
		T pop_back() {
			std::scoped_lock lock(muxQueue);
			auto t = std::move(deqQueue.back());
			deqQueue.pop_back();
			return t;
		}

		// return true if Queue has no items
		bool empty() {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			return deqQueue.empty();
		}

		// return number of items in Queue
		size_t count() {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			return deqQueue.size();
		}

		// return number of items in Queue
		size_t count() const {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			return deqQueue.size();
		}

		// clears Queue
		void clear() {
			std::scoped_lock lock(muxQueue); // protects anything else from running
			deqQueue.clear();
		}

		typename std::deque<T>::const_iterator begin() const {
			std::unique_lock lock(muxQueue); // protects anything else from running
			return deqQueue.begin();
		}

		typename std::deque<T>::const_iterator end() const {
			std::unique_lock lock(muxQueue); // protects anything else from running
			return deqQueue.end();
		}

		void wait() {
			while (empty()) {
				std::unique_lock<std::mutex> ul(muxBlocking);
				cvBlocking.wait(ul); // Wait for mutex to unlock
			}

		}

		void lock() {
			std::unique_lock<std::mutex> ul(muxBlocking);
			cvBlocking.wait(ul); // Wait for mutex to unlock
		}

		void unlock() {
			std::unique_lock<std::mutex> ul(muxBlocking);
			cvBlocking.notify_one();
		}


	protected:
		mutable std::mutex muxQueue; // protects access to deque
		std::deque<T> deqQueue;
		std::condition_variable cvBlocking;
		std::mutex muxBlocking;
	};

