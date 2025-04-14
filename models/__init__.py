from models.user import User
from models.restaurant_chain import RestaurantChain
from models.restaurant_outlet import RestaurantOutlet
from models.subscription import Subscription
from models.menu_management import MenuCategory   ,MenuItem
from models.order_management import Order, OrderItem    
from models.table_management import Area,Table

# Register all models
__all__ = ['User', 'RestaurantChain', 'RestaurantOutlet','Subscription','MenuCategory','MenuItem','Order','OrderItem','Area','Table']