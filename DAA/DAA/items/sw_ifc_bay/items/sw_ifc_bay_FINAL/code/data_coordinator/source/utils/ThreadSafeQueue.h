#pragma once

#include <queue>
#include <mutex>
#include <condition_variable>
#include <optional>

template <typename T>
class MessageQueue {
public:
    explicit MessageQueue(size_t max_size) : m_max_size(max_size) {}

    MessageQueue(const MessageQueue&) = delete;
    MessageQueue& operator=(const MessageQueue&) = delete;

    bool try_push(T value) {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_queue.size() >= m_max_size) {
            return false; // Cola llena
        }
        m_queue.push(std::move(value));
        m_cond.notify_one();
        return true;
    }

    std::optional<T> try_pop() {
        std::lock_guard<std::mutex> lock(m_mutex);
        if (m_queue.empty()) {
            return std::nullopt;
        }
        T value = std::move(m_queue.front());
        m_queue.pop();
        return value;
    }
    
    bool is_empty() const {
        std::lock_guard<std::mutex> lock(m_mutex);
        return m_queue.empty();
    }

private:
    size_t m_max_size;
    std::queue<T> m_queue;
    mutable std::mutex m_mutex;
    std::condition_variable m_cond;
};
