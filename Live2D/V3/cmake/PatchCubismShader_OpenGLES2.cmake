# Keep the fix reproducible: Cubism Framework is downloaded and git-ignored.
set(_shader_file "${LIVE2D_ROOT}/V3/Framework/src/Rendering/OpenGL/CubismShader_OpenGLES2.cpp")
file(READ "${_shader_file}" _shader_source)
string(REPLACE "\r\n" "\n" _shader_source "${_shader_source}")
set(_old_release [=[void CubismShader_OpenGLES2::ReleaseShaderProgram()
{
    for (csmUint32 i = 0; i < _shaderSets.GetSize(); i++)
    {
        if (_shaderSets[i]->ShaderProgram)
        {
            glDeleteProgram(_shaderSets[i]->ShaderProgram);
            _shaderSets[i]->ShaderProgram = 0;
            CSM_DELETE(_shaderSets[i]);
        }
    }
}]=])
set(_new_release [=[void CubismShader_OpenGLES2::ReleaseShaderProgram()
{
    // LIVE2D_PY_UNIQUE_SHADER_RELEASE: blend variants share program IDs.
    for (csmUint32 i = 0; i < _shaderSets.GetSize(); i++)
    {
        const GLuint program = _shaderSets[i]->ShaderProgram;
        if (program)
        {
            GLint currentProgram = 0;
            glGetIntegerv(GL_CURRENT_PROGRAM, &currentProgram);
            if (static_cast<GLuint>(currentProgram) == program)
            {
                glUseProgram(0);
            }
            glDeleteProgram(program);
            for (csmUint32 j = i; j < _shaderSets.GetSize(); j++)
            {
                if (_shaderSets[j]->ShaderProgram == program)
                {
                    _shaderSets[j]->ShaderProgram = 0;
                }
            }
        }
        CSM_DELETE(_shaderSets[i]);
    }
    _shaderSets.Clear();
}]=])
string(FIND "${_shader_source}" "LIVE2D_PY_UNIQUE_SHADER_RELEASE" _already_patched)
if(_already_patched EQUAL -1)
    string(FIND "${_shader_source}" "${_old_release}" _release_offset)
    if(_release_offset EQUAL -1)
        message(FATAL_ERROR "Cubism shader release changed; review the unique-program cleanup patch.")
    endif()
    string(REPLACE "${_old_release}" "${_new_release}" _shader_source "${_shader_source}")
    file(WRITE "${_shader_file}" "${_shader_source}")
endif()
