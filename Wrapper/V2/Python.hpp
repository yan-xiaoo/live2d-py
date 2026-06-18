#pragma once
#ifndef Py_LIMITED_API
#define Py_LIMITED_API 0x03020000
#endif
#include <Python.h>
#ifndef Py_IsNone
#define Py_IsNone(o) (o == Py_None)
#endif
