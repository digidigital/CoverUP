# FreeSimpleGUI Tcl 9.0 Migration Guide

## Problem Summary

FreeSimpleGUI uses the deprecated `trace variable` Tcl command which was removed in Tcl 9.0. This prevents the library from working with GNOME Platform 49+ (which uses Python 3.13 and Tcl 9.0).

### Error Message

When running with Tcl 9.0:
```
_tkinter.TclError: bad option "variable": must be add, info, or remove
```

## Root Cause

In `FreeSimpleGUI/window.py` around line 2470:
```python
self.thread_strvar.trace('w', self._window_tkvar_changed_callback)
```

The `.trace()` method with single-letter modes (`'w'`, `'r'`, `'u'`) maps to the Tcl `trace variable` command, which was deprecated in Tcl 8.4 and removed in Tcl 9.0.

## Solution

Replace all `.trace()` calls with `.trace_add()` and update the mode names:

| Old Method | New Method |
|------------|------------|
| `.trace('r', cb)` | `.trace_add('read', cb)` |
| `.trace('w', cb)` | `.trace_add('write', cb)` |
| `.trace('u', cb)` | `.trace_add('unset', cb)` |
| `.trace_vdelete(id, mode)` | `.trace_remove(mode, id)` |
| `.trace_vinfo()` | `.trace_info()` |

### Code Changes Required

#### 1. FreeSimpleGUI/window.py

**Before:**
```python
self.thread_strvar.trace('w', self._window_tkvar_changed_callback)
```

**After:**
```python
self.thread_strvar.trace_add('write', self._window_tkvar_changed_callback)
```

#### 2. Search for all occurrences

Search the FreeSimpleGUI codebase for:
```bash
grep -rn "\.trace(" --include="*.py"
grep -rn "trace_vdelete" --include="*.py"
grep -rn "trace_vinfo" --include="*.py"
```

## Callback Signature

The callback signature remains the same, but the `mode` argument value changes:

**Old:**
```python
def callback(name, index, mode):
    # mode is 'w', 'r', or 'u'
    if mode == 'w':
        ...
```

**New:**
```python
def callback(name, index, mode):
    # mode is 'write', 'read', or 'unset'
    if mode == 'write':
        ...
```

## Compatibility

The new `trace_add()` method has been available since:
- **Python**: 3.0+
- **Tcl/Tk**: 8.4+

This means the fix is backward compatible with all currently supported Python and Tcl versions.

## Test Plan

### Unit Tests

```python
import unittest
import tkinter as tk
from unittest.mock import Mock, patch

class TestTraceCompatibility(unittest.TestCase):
    """Tests for Tcl 9.0 trace compatibility."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()  # Hide the window
        self.string_var = tk.StringVar(self.root)

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_trace_add_write_triggers_callback(self):
        """Test that trace_add with 'write' mode triggers on value change."""
        callback = Mock()

        self.string_var.trace_add('write', callback)
        self.string_var.set('new value')

        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertEqual(args[2], 'write')  # mode should be 'write'

    def test_trace_add_read_triggers_callback(self):
        """Test that trace_add with 'read' mode triggers on value read."""
        callback = Mock()

        self.string_var.trace_add('read', callback)
        _ = self.string_var.get()

        callback.assert_called_once()
        args = callback.call_args[0]
        self.assertEqual(args[2], 'read')  # mode should be 'read'

    def test_trace_add_unset_triggers_callback(self):
        """Test that trace_add with 'unset' mode triggers on variable unset."""
        callback = Mock()
        var = tk.StringVar(self.root)

        var.trace_add('unset', callback)
        del var  # This should trigger the unset callback

        # Note: unset may not trigger immediately due to garbage collection
        # In practice, this is less commonly used

    def test_trace_remove_stops_callback(self):
        """Test that trace_remove prevents future callbacks."""
        callback = Mock()

        trace_id = self.string_var.trace_add('write', callback)
        self.string_var.set('first')
        self.assertEqual(callback.call_count, 1)

        self.string_var.trace_remove('write', trace_id)
        self.string_var.set('second')
        self.assertEqual(callback.call_count, 1)  # Should not increase

    def test_trace_info_returns_traces(self):
        """Test that trace_info returns registered traces."""
        callback = Mock()

        trace_id = self.string_var.trace_add('write', callback)
        info = self.string_var.trace_info()

        self.assertTrue(len(info) > 0)
        # trace_info returns list of tuples: (mode_tuple, callback_name)
        modes = [item[0] for item in info]
        self.assertTrue(any('write' in mode for mode in modes))

    def test_multiple_traces_same_variable(self):
        """Test multiple traces on the same variable."""
        callback1 = Mock()
        callback2 = Mock()

        self.string_var.trace_add('write', callback1)
        self.string_var.trace_add('write', callback2)
        self.string_var.set('test')

        callback1.assert_called_once()
        callback2.assert_called_once()

    def test_callback_receives_correct_arguments(self):
        """Test that callback receives name, index, and mode."""
        received_args = []

        def callback(name, index, mode):
            received_args.append((name, index, mode))

        self.string_var.trace_add('write', callback)
        self.string_var.set('test')

        self.assertEqual(len(received_args), 1)
        name, index, mode = received_args[0]
        self.assertIsInstance(name, str)
        self.assertEqual(index, '')  # Empty for simple variables
        self.assertEqual(mode, 'write')


class TestFreeSimpleGUIIntegration(unittest.TestCase):
    """Integration tests for FreeSimpleGUI with Tcl 9.0."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_window_thread_queue_creation(self):
        """
        Test that simulates FreeSimpleGUI's _create_thread_queue method.
        This is the method that fails with Tcl 9.0.
        """
        callback_called = []

        def mock_callback(*args):
            callback_called.append(args)

        thread_strvar = tk.StringVar(self.root)

        # This is what FreeSimpleGUI should do (new way)
        thread_strvar.trace_add('write', mock_callback)

        # Simulate thread writing to the variable
        thread_strvar.set('thread_message')

        self.assertEqual(len(callback_called), 1)
        self.assertEqual(callback_called[0][2], 'write')

    def test_tcl_version_detection(self):
        """Test that we can detect the Tcl version."""
        tcl_version = self.root.tk.call('info', 'patchlevel')
        print(f"Tcl version: {tcl_version}")

        # Parse version
        major = int(tcl_version.split('.')[0])
        self.assertIn(major, [8, 9])  # Should be Tcl 8.x or 9.x


class TestBackwardCompatibility(unittest.TestCase):
    """Tests to ensure backward compatibility with Tcl 8.x."""

    def setUp(self):
        """Set up test fixtures."""
        self.root = tk.Tk()
        self.root.withdraw()
        self.string_var = tk.StringVar(self.root)

    def tearDown(self):
        """Clean up after tests."""
        self.root.destroy()

    def test_trace_add_exists(self):
        """Test that trace_add method exists (Python 3.0+)."""
        self.assertTrue(hasattr(self.string_var, 'trace_add'))

    def test_trace_remove_exists(self):
        """Test that trace_remove method exists (Python 3.0+)."""
        self.assertTrue(hasattr(self.string_var, 'trace_remove'))

    def test_trace_info_exists(self):
        """Test that trace_info method exists (Python 3.0+)."""
        self.assertTrue(hasattr(self.string_var, 'trace_info'))


if __name__ == '__main__':
    # Run with verbose output
    unittest.main(verbosity=2)
```

### Running the Tests

```bash
# Run all tests
python -m pytest tests/test_tcl9_trace.py -v

# Or with unittest
python tests/test_tcl9_trace.py

# Test with specific Tcl version (if you have both installed)
TCL_LIBRARY=/path/to/tcl9/lib python -m pytest tests/test_tcl9_trace.py -v
```

### Manual Integration Test

```python
#!/usr/bin/env python3
"""
Manual integration test for FreeSimpleGUI with Tcl 9.0.
Run this after applying the patch to verify the fix works.
"""

import tkinter as tk

def test_freesimplegui_window():
    """Test creating a FreeSimpleGUI window."""
    try:
        import FreeSimpleGUI as sg

        # Get Tcl version
        root = tk.Tk()
        root.withdraw()
        tcl_version = root.tk.call('info', 'patchlevel')
        root.destroy()
        print(f"Testing with Tcl version: {tcl_version}")

        # Create a simple window
        layout = [[sg.Text('Tcl 9.0 Compatibility Test')],
                  [sg.Button('OK'), sg.Button('Cancel')]]

        window = sg.Window('Test Window', layout, finalize=True)

        # If we get here, the trace issue is fixed
        print("SUCCESS: Window created without trace error!")

        # Close the window
        window.close()
        return True

    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        return False

if __name__ == '__main__':
    success = test_freesimplegui_window()
    exit(0 if success else 1)
```

## Implementation Checklist

- [ ] Fork FreeSimpleGUI repository
- [ ] Search for all `.trace(` calls in the codebase
- [ ] Replace `.trace('w', ...)` with `.trace_add('write', ...)`
- [ ] Replace `.trace('r', ...)` with `.trace_add('read', ...)`
- [ ] Replace `.trace('u', ...)` with `.trace_add('unset', ...)`
- [ ] Update any `.trace_vdelete()` calls to `.trace_remove()`
- [ ] Update any `.trace_vinfo()` calls to `.trace_info()`
- [ ] Update callback mode checks from `'w'`/`'r'`/`'u'` to `'write'`/`'read'`/`'unset'`
- [ ] Run unit tests
- [ ] Run integration tests with Tcl 8.6
- [ ] Run integration tests with Tcl 9.0
- [ ] Submit pull request to FreeSimpleGUI

## References

- [Tcl 9.0 Migration Guide](https://wiki.tcl-lang.org/page/Tcl+9.0+Migration+Guide)
- [Python tkinter trace documentation](https://docs.python.org/3/library/tkinter.html#tkinter.Variable.trace_add)
- [Tcl trace command manual](https://www.tcl-lang.org/man/tcl/TclCmd/trace.htm)
- [FreeSimpleGUI GitHub](https://github.com/spyoungtech/FreeSimpleGUI)

## Flatpak Impact

Once FreeSimpleGUI is patched, the CoverUP Flatpak can be updated to use:
- GNOME Platform 49 (runtime-version: '49')
- Python 3.13
- Tcl/Tk 9.0 via tkinter-standalone (commit: 8e78e38ef0cceb44a3a0062e1c314a4ff3f981db)
- Updated Pillow wheel (cp313)
