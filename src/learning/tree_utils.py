from sklearn.tree import _tree
import numpy as np

def tree_to_json(tree, feature_names):
    """
    Converts a Scikit-Learn DecisionTree object into a JSON-serializable dictionary.
    
    Args:
        tree: The sklearn.tree.DecisionTreeClassifier (or Regressor) object
        feature_names: List of feature names strings
        
    Returns:
        dict: A recursive dictionary representing the tree structure
    """
    tree_ = tree.tree_
    feature_name = [
        feature_names[i] if i != _tree.TREE_UNDEFINED else "undefined!"
        for i in tree_.feature
    ]
    
    def recurse(node):
        name = feature_name[node]
        threshold = tree_.threshold[node]
        
        # Leaf node
        if tree_.feature[node] == _tree.TREE_UNDEFINED:
            # Get class distribution
            value = tree_.value[node][0]
            predicted_class = int(np.argmax(value))
            
            return {
                "name": f"Class {predicted_class}",
                "attributes": {
                    "samples": int(tree_.n_node_samples[node]),
                    "gini": float(tree_.impurity[node]),
                    "value": [int(v) for v in value]
                }
            }
        # Internal node
        else:
            return {
                "name": f"{name} <= {threshold:.2f}",
                "attributes": {
                    "samples": int(tree_.n_node_samples[node]),
                    "gini": float(tree_.impurity[node])
                },
                "children": [
                    recurse(tree_.children_left[node]),
                    recurse(tree_.children_right[node])
                ]
            }

    return recurse(0)
