import importlib

def check(name, alt=None):
    try:
        mod = importlib.import_module(name)
        ver = getattr(mod, "__version__", "unknown")
        print(f"{name}: installed, version={ver}")
        return True
    except Exception as e:
        if alt:
            try:
                mod = importlib.import_module(alt)
                ver = getattr(mod, "__version__", "unknown")
                print(f"{alt} (as {name}): installed, version={ver}")
                return True
            except Exception:
                pass
        print(f"{name}: import error: {e}")
        return False

if __name__ == '__main__':
    check('streamlit')
    check('faiss', alt='faiss_cpu')
    check('langchain_huggingface')
    check('langchain')
