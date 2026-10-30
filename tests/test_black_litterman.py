import numpy as np
import pytest
from engine.black_litterman import black_litterman_posterior, market_implied_returns, optimise_black_litterman


def sample_inputs():
    return (np.array([[.040,.012,.004],[.012,.090,.010],[.004,.010,.010]]),
            np.array([.5,.3,.2]))


def test_market_implied_returns_follow_reverse_optimisation():
    cov, weights = sample_inputs()
    assert np.allclose(market_implied_returns(cov, weights, 2.0), 2.0*cov@weights)


def test_posterior_moves_towards_high_confidence_view():
    cov, weights = sample_inputs()
    P, target = np.array([[1.,-1.,0.]]), np.array([.12])
    prior = market_implied_returns(cov, weights)
    low = black_litterman_posterior(cov, weights, P, target, view_confidences=np.array([.2]))
    high = black_litterman_posterior(cov, weights, P, target, view_confidences=np.array([.9]))
    assert abs((P@high["posterior_returns"])[0]-target[0]) < abs((P@low["posterior_returns"])[0]-target[0])
    assert abs((P@high["posterior_returns"])[0]-target[0]) < abs((P@prior)[0]-target[0])


def test_optimizer_respects_long_only_and_weight_caps():
    cov, weights = sample_inputs()
    post = black_litterman_posterior(cov, weights, [[1.,-1.,0.]], [.10])
    result = optimise_black_litterman(post["posterior_returns"], cov, max_weight=.6)
    assert result["weights"].sum() == pytest.approx(1)
    assert (result["weights"] >= 0).all() and (result["weights"] <= .6+1e-8).all()


def test_rejects_invalid_views_and_infeasible_caps():
    cov, weights = sample_inputs()
    with pytest.raises(ValueError):
        black_litterman_posterior(cov, weights, np.ones((2,2)), [.1])
    with pytest.raises(ValueError, match="infeasible"):
        optimise_black_litterman(np.array([.1,.08,.04]), cov, max_weight=.2)
