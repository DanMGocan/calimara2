
try:
    from app.main import app
    print('App imported successfully')
    print('Number of routes:', len(app.routes))
    # Show admin routes specifically
    for route in app.routes:
        if hasattr(route, 'path') and 'admin' in route.path:
            print(f"Admin route: {route.methods} {route.path}")
except Exception as e:
    print('Error importing app:', e)
    import traceback
    traceback.print_exc()

if __name__ == "__main__":
    check_app()

