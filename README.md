# 🚀 JavaScript & React Interview Masterclass Repository

An interactive, production-ready React application built with Vite to demonstrate and test key JavaScript concepts:
1. **Debouncing** (Search autocomplete API visualizer with delay sliders, immediate mode, cancel & flush)
2. **Throttling** (Scroll tracker rate limiter comparing raw vs throttled events)
3. **`map()`** (Dynamic product cards rendering)
4. **`filter()`** (Multi-criteria live search and category filters)
5. **`reduce()`** (Real-time cart total, subtotal, and tax aggregation)
6. **Polyfills Test Suite** (Automated unit test suite comparing native methods vs custom `myMap`, `myFilter`, `myReduce`, `myDebounce`, and `myThrottle`)

---

## 🛠️ Getting Started

### Prerequisites
- **Node.js**: v18.0.0 or higher
- **npm**: v9.0.0 or higher

### Installation & Launching

1. Open terminal inside this directory (`c:\Project\Interview`):
```bash
npm install
```

2. Start the local development server:
```bash
npm run dev
```

3. Open your browser at `http://localhost:3000`.

---

## 📁 Repository Architecture

```
Interview/
├── index.html                  # HTML entry point with Google Fonts
├── package.json                # Dependencies and scripts
├── vite.config.js              # Vite configuration
├── README.md                   # Repository documentation
└── src/
    ├── main.jsx                # React DOM root render
    ├── App.jsx                 # Main layout and tab navigation
    ├── index.css               # Design system (Dark mode, glassmorphism)
    ├── utils/
    │   └── polyfills.js        # Prototype polyfills (myMap, myFilter, myReduce, myDebounce, myThrottle)
    └── components/
        ├── DebounceDemo.jsx    # Machine coding demo for Debounce
        ├── ThrottleDemo.jsx    # Machine coding demo for Throttle
        ├── ArrayMethodsDemo.jsx# E-Commerce demo using map, filter, & reduce
        ├── PolyfillTester.jsx  # Automated polyfill unit testing suite
        └── InterviewCheatSheet.jsx # FAQs and 1-line memory tricks
```

---
*Created for Senior Frontend Technical Interview Preparation.*
